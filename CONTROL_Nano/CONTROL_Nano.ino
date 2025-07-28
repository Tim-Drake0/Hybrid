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

struct DAQ_Payload // ACK Payload from DAQ
{
  bool CC1 = 0; // Continuity channel 1
  bool CC2 = 0; // Continuity channel 2
  char PTC1[5] = {}; // PT channel 1 (tank)
  char LC1[7] = {}; // Load Cell reading
};
uint8_t switchstate[9];
DAQ_Payload daqstate;

#define RFM95_CS 9
#define RFM95_RST 10
#define RFM95_INT 2
#define RF95_FREQ 433.9869
int RFM95_PWR = 23;
RH_RF95 rf95(RFM95_CS, RFM95_INT);

LiquidCrystal lcd(RS,EN,D4,D5,D6,D7); // Initialize LCD object

bool CON_ERR = 0; // Track if there was successful transmission
bool RECV_ERR = 0;

// Loop parameters
const int dt_tx = 100; // Loop transmission speed [ms]
const int dt_lcd = 1000; // Loop lcd print speed [ms] 
long int last_time_tx = 0; // Last transmission completion time tracking [ms]
long int last_time_lcd = 0; // Last lcd time tracking [ms]
int switch_data_count = 0;

bool lowBattery = 0;
float maxThrust = 0;
float thisThrust = 0;

void printlcd(uint8_t buf[9], int switch_data_count) {
  lcd.clear();
  lcd.setCursor(0,0); // set cursor to beginning of top row
  lcd.print("TANK:"); // Display tank pressure
  lcd.print(word(buf[4], buf[5]));

  lcd.setCursor(13,0); // set cursor to column 10 of row 0
  lcd.print("C");
  lcd.print(!buf[0]);
  lcd.print(!buf[1]);

  lcd.setCursor(0,1); // Set cursor to beginning of botton row
  lcd.print("LC:");
  thisThrust = word(buf[2], buf[3])*0.939416365405;
  if(switchstate[6] == 1){
    if(thisThrust > maxThrust){
      lcd.print(thisThrust);
      maxThrust = thisThrust;
    } else {
      lcd.print(maxThrust);
    }
  } else {
    maxThrust = 0;
    lcd.print(thisThrust);
  }
  
  if (CON_ERR) { // If transmission failed
    lcd.setCursor(10,1); 
    lcd.print("CON_ERR");
    return;
  }

  if(word(buf[6], buf[7])*0.0213 > 7.5){ // check if low battery and only display that
    if(switch_data_count < 21){
      lcd.setCursor(10,1); 
      lcd.print("RS:"); 
      if( abs(rf95.lastRssi()) >= 100){
        lcd.setCursor(13,1);
      } else {
        lcd.setCursor(14,1);
      }
      lcd.print(String(abs(rf95.lastRssi())));
    } else {
      lcd.setCursor(9,1); 
      lcd.print("BT:"); 
      if(word(buf[6], buf[7])*0.0213<7.5){ 
        lcd.print("LOW!"); // If low battery for a 2 cell
      } else{
      lcd.print(word(buf[6], buf[7])*0.0213);// word(high,low)
      }
    }
  } else {
    lcd.setCursor(9,1); 
    lcd.print("BT:"); 
    lcd.print("LOW!"); // If low battery for a 2 cell
  }
}

void readswitches(void) {
  switchstate[0] = !digitalRead(SWP1); // get state of switch 1 for transmission
  switchstate[1] = !digitalRead(SWP2); // get state of switch 2 for transmission
  switchstate[2] = !digitalRead(SWP3); // get state of switch 3 for transmission
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
  // LCD setup
  lcd.begin(16,2); // LCD has 16 cols, 2 rows
  lcd.setCursor(0,0); // Set cursor at beginning
  lcd.print("Sup..."); // Print startup message
  lcd.setCursor(0,1); // Set cursor at beginning of second row
  lcd.print("Starting Radio");
  delay(1000);
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
    lcd.clear(); 
    lcd.setCursor(0,0);
    lcd.print("Radio Failed! :(");
    while (1);
  }
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  if (!rf95.setFrequency(RF95_FREQ)) {
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print("setFrequency failed! :(");
    while (1);
  }
  // Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on
  // The default transmitter power is 13dBm, using PA_BOOST.
  // If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then 
  // you can set transmitter powers from 5 to 23 dBm:
  rf95.setTxPower(RFM95_PWR, false);

  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("Set Freq to: "); lcd.print(RF95_FREQ);
  lcd.setCursor(0,1);
  lcd.print("Radio Power: "); lcd.print(RFM95_PWR);
  delay(1000); 

  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("Startup");
  lcd.setCursor(0,1);
  lcd.print("Complete");
  delay(1000); // delay for begin
}

void loop() {
  // TRANSCEIVER CODE ====================================================================================================
  uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
  uint8_t len = sizeof(buf);
  if (millis()-last_time_tx > dt_tx) { 
    readswitches(); // record state of switches
    rf95.send(switchstate, sizeof(switchstate));

    CON_ERR = 0;// connection error bool to false
    rf95.waitPacketSent();
    // Now wait for a reply
    
    if (rf95.waitAvailableTimeout(5000)) { 
      // Should be a reply message for us now   
      rf95.recv(buf, &len);
    } else {
      CON_ERR = 1;
    }
    last_time_tx = millis(); // Save time at end of transceiver loop for tracking
  }
  // Display DAQ on LCD
  if (millis()-last_time_lcd > dt_lcd) {
    switch_data_count++;
    printlcd(buf,switch_data_count); // Prints current DAQ data on LCD
    last_time_lcd = millis(); // Save time at end of lcd display loop for tracking
    if(switch_data_count == 40){switch_data_count = 0;}
  }
        
}
