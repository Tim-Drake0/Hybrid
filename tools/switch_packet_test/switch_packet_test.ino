// switch_packet_test.ino -- Teensy 4.1 stand-in for the ECU, for bench
// testing the ground station radio link.
//
// Receives the ground station telemetry (serial_writer.GroundStationRadioTelem)
// on Serial1 and immediately sends back an ECU telemetry packet
// (serial_reader.ECURadioTelem) whose ecuStatus_e is the commands_e it just
// received -- i.e. it echoes the commands back as status -- with the
// PWR/PROP/NAV GOOD status bits (b13-b15) hardcoded to 1. All other ECU
// fields are 0 except the timestamp. Everything received/sent is also
// printed to the USB serial monitor.
//
// Wiring (both sides are 3.3 V logic -- no level shifting needed):
//   Pi GPIO14 / UART0 TX (header pin 8)   ->  Teensy pin 0 (RX1)
//   Pi GPIO15 / UART0 RX (header pin 10)  <-  Teensy pin 1 (TX1)
//   Pi GND (e.g. header pin 6)            --  Teensy GND
//
// Framing (both directions):
//   START0 START1 | ID | LEN | PAYLOAD | CRC | EF BE
//   CRC = XOR of ID, LEN and the payload bytes. Payloads are packed and
//   little-endian, so the structs below are memcpy'd straight in/out.
//
//   ground -> ECU : DE AD | 0x10 | 6  | GroundStation_Payload
//   ECU -> ground : AB CD | 0x20 | 77 | ECU_Payload

#define RADIO_SERIAL      Serial1    // RX1 = pin 0, TX1 = pin 1
#define RADIO_BAUD        115200     // gui_settings.RADIO_BAUD_RATE
#define RAW_HEX_DUMP      0          // 1 = also print every received byte in hex (debug)
#define ACTIVITY_LED      13         // on-board LED blinks while bytes arrive

#define TELEM_FRAME_START_0 0xAB
#define TELEM_FRAME_START_1 0xCD
#define CMD_FRAME_START_0   0xDE
#define CMD_FRAME_START_1   0xAD
#define FRAME_END_0         0xEF
#define FRAME_END_1         0xBE
#define MAX_PAYLOAD_LEN     128

#define CMD_GND_TELEM       0x10     // serial_writer.CMD_GND_TELEM
#define ECU_TELEM_ID        0x20     // serial_reader.ECU_TELEM_ID

// ecuStatus_e bits that only exist in the status (not echoed commands)
#define ECHO_COMMAND_MASK     0x1FFF   // b0-b12 mirror commands_e
#define STATUS_PWR_GOOD_BIT   13       // pwrGoodStatus_b
#define STATUS_PROP_GOOD_BIT  14       // propGoodStatus_b
#define STATUS_NAV_GOOD_BIT   15       // navGoodStatus_b

// == Payloads (keep in sync with the Python dataclasses) =======================
// serial_writer.GroundStationRadioTelem.createPayload() "<IH"
struct __attribute__((packed)) GroundStation_Payload {
  uint32_t timestamp_ms;
  uint16_t commands_e;      // bitfield, see COMMAND_NAMES
};

// serial_reader.ECURadioTelem.readBuffer() "<IHffffbfffiiiiiiBfffBf"
struct __attribute__((packed)) ECU_Payload {
  uint32_t timestamp;
  uint16_t ecuStatus_e;     // same bit order as commands_e
  float    pt1;
  float    pt2;
  float    pt3;
  float    pt4;
  int8_t   rssi;
  float    boardTemp_c;
  float    battery_V;
  float    batteryCurrent_A;
  int32_t  altitude_ft;
  int32_t  verticalVelocity_fps;
  int32_t  maxVel_fps;
  int32_t  maxMach;
  int32_t  maxAlt_ft;
  int32_t  maxG;
  uint8_t  gpsFixValid_b;
  float    gpsLat_deg;
  float    gpsLon_deg;
  float    gpsAlt_ft;
  uint8_t  gpsNumSV;
  float    gpsHDOP;
};
static_assert(sizeof(GroundStation_Payload) == 6,  "GroundStation_Payload must be 6 bytes");
static_assert(sizeof(ECU_Payload)           == 77, "ECU_Payload must be 77 bytes");

// Bit N of commands_e / ecuStatus_e (bit order of the *Cmd_b / *Status_b
// fields in GroundStationRadioTelem / ECURadioTelem).
static const char *COMMAND_NAMES[] = {
  "FILL_VLV",     // b0
  "VENT_VLV",     // b1
  "MOV_VLV",      // b2
  "SPARE_VLV",    // b3
  "RADIO_EN",     // b4
  "CAMERA_EN",    // b5
  "AUTO_FIRE_EN", // b6
  "RECORD_EN",    // b7
  "SPARE1_EN",    // b8
  "SPARE2_EN",    // b9
  "ARM",          // b10
  "PYRO_FIRE",    // b11
  "PYRO_CH",      // b12  (1 = channel 1, 0 = channel 2)
};
static const uint8_t NUM_COMMANDS = sizeof(COMMAND_NAMES) / sizeof(COMMAND_NAMES[0]);

static GroundStation_Payload gnd_pkt;
static ECU_Payload           ecu_pkt;

// == Frame parser =============================================================
typedef enum { WAIT_START0, WAIT_START1, READ_ID, READ_LEN, READ_PAYLOAD, READ_CRC, READ_END0, READ_END1 } ParseState;

static ParseState parse_state = WAIT_START0;
static uint8_t    parse_buf[2 + MAX_PAYLOAD_LEN];   // ID, LEN, payload
static uint8_t    parse_idx = 0;
static uint8_t    parse_len = 0;

// Link statistics
static uint32_t rx_bytes     = 0;     // every byte seen on RX1, valid or not
static uint32_t rx_packets   = 0;
static uint32_t tx_packets   = 0;
static uint32_t crc_errors   = 0;
static uint32_t frame_errors = 0;
static uint32_t last_rx_ms   = 0;
static int32_t  last_commands = -1;   // -1 = nothing received yet

static uint8_t crc8(const uint8_t *data, uint8_t len) {
  uint8_t crc = 0x00;
  while (len--) crc ^= *data++;
  return crc;
}

static void sendFrame(uint8_t start0, uint8_t start1, uint8_t id, const void *payload, uint8_t len) {
  uint8_t buf[2 + 2 + MAX_PAYLOAD_LEN + 1 + 2];
  uint8_t i = 0;
  buf[i++] = start0;
  buf[i++] = start1;
  buf[i++] = id;
  buf[i++] = len;
  memcpy(&buf[i], payload, len);
  i += len;
  buf[i++] = crc8(&buf[2], 2 + len);
  buf[i++] = FRAME_END_0;
  buf[i++] = FRAME_END_1;
  RADIO_SERIAL.write(buf, i);
}

static void printCommands(uint16_t commands, uint32_t timestamp_ms) {
  Serial.print(F("[gnd t="));
  Serial.print(timestamp_ms);
  Serial.print(F(" ms] commands_e=0x"));
  if (commands < 0x1000) Serial.print('0');
  if (commands < 0x100)  Serial.print('0');
  if (commands < 0x10)   Serial.print('0');
  Serial.println(commands, HEX);

  for (uint8_t i = 0; i < NUM_COMMANDS; i++) {
    Serial.print(F("  "));
    Serial.print(COMMAND_NAMES[i]);
    for (uint8_t pad = strlen(COMMAND_NAMES[i]); pad < 13; pad++) Serial.print(' ');
    Serial.println(bitRead(commands, i) ? F("ON") : F("off"));
  }
}

static void handlePacket(uint8_t id, const uint8_t *payload, uint8_t len) {
  if (id != CMD_GND_TELEM) return;                 // some other command -- ignore
  if (len != sizeof(GroundStation_Payload)) { frame_errors++; return; }

  memcpy(&gnd_pkt, payload, sizeof(gnd_pkt));
  rx_packets++;
  last_rx_ms = millis();

  // Echo: report the received commands (b0-b12) back as ECU status, plus
  // the status-only GOOD bits (b13-b15), hardcoded good for now.
  memset(&ecu_pkt, 0, sizeof(ecu_pkt));
  ecu_pkt.timestamp   = millis();
  ecu_pkt.ecuStatus_e = (gnd_pkt.commands_e & ECHO_COMMAND_MASK)
                      | (1 << STATUS_PWR_GOOD_BIT)
                      | (1 << STATUS_PROP_GOOD_BIT)
                      | (1 << STATUS_NAV_GOOD_BIT);
  sendFrame(TELEM_FRAME_START_0, TELEM_FRAME_START_1, ECU_TELEM_ID, &ecu_pkt, sizeof(ecu_pkt));
  tx_packets++;

  if ((int32_t)gnd_pkt.commands_e != last_commands) {   // only print on change
    printCommands(gnd_pkt.commands_e, gnd_pkt.timestamp_ms);
    last_commands = gnd_pkt.commands_e;
  }
}

static void parseByte(uint8_t b) {
  switch (parse_state) {
    case WAIT_START0:
      if (b == CMD_FRAME_START_0) parse_state = WAIT_START1;
      break;
    case WAIT_START1:
      if (b == CMD_FRAME_START_1)      parse_state = READ_ID;
      else if (b != CMD_FRAME_START_0) parse_state = WAIT_START0;
      break;
    case READ_ID:
      parse_buf[0] = b;
      parse_state = READ_LEN;
      break;
    case READ_LEN:
      if (b > MAX_PAYLOAD_LEN) { frame_errors++; parse_state = WAIT_START0; break; }
      parse_len = b;
      parse_buf[1] = b;
      parse_idx = 2;
      parse_state = (parse_len > 0) ? READ_PAYLOAD : READ_CRC;
      break;
    case READ_PAYLOAD:
      parse_buf[parse_idx++] = b;
      if (parse_idx >= 2 + parse_len) parse_state = READ_CRC;
      break;
    case READ_CRC:
      if (crc8(parse_buf, 2 + parse_len) == b) {
        parse_state = READ_END0;
      } else {
        crc_errors++;
        parse_state = WAIT_START0;
      }
      break;
    case READ_END0:
      if (b == FRAME_END_0) parse_state = READ_END1;
      else { frame_errors++; parse_state = WAIT_START0; }
      break;
    case READ_END1:
      parse_state = WAIT_START0;
      if (b == FRAME_END_1) handlePacket(parse_buf[0], &parse_buf[2], parse_len);
      else frame_errors++;
      break;
  }
}

// == Arduino ==================================================================
// All printing goes to `Serial`, which on a Teensy is the USB port to the PC
// (Tools > USB Type must include "Serial"). Serial1 is the radio link.
void setup() {
  Serial.begin(115200);                // USB -- baud is ignored, always full USB speed
  RADIO_SERIAL.begin(RADIO_BAUD);
  pinMode(ACTIVITY_LED, OUTPUT);
  while (!Serial && millis() < 3000) {}

  Serial.print(F("ECU echo test -- Serial1 RX pin 0 / TX pin 1 @ "));
  Serial.print(RADIO_BAUD);
  Serial.println(F(" baud, printing to USB"));
}

void loop() {
  static uint32_t last_byte_ms = 0;
  while (RADIO_SERIAL.available()) {
    uint8_t b = RADIO_SERIAL.read();
    rx_bytes++;
    last_byte_ms = millis();
#if RAW_HEX_DUMP
    if (b < 0x10) Serial.print('0');
    Serial.print(b, HEX);
    Serial.print(b == FRAME_END_1 ? '\n' : ' ');
#endif
    parseByte(b);
  }
  digitalWrite(ACTIVITY_LED, millis() - last_byte_ms < 50);

  static uint32_t last_status_ms = 0;
  if (millis() - last_status_ms >= 2000) {
    last_status_ms = millis();
    Serial.print(F("-- rx_bytes="));  Serial.print(rx_bytes);
    Serial.print(F("  rx="));         Serial.print(rx_packets);
    Serial.print(F("  tx="));         Serial.print(tx_packets);
    Serial.print(F("  crc_err="));    Serial.print(crc_errors);
    Serial.print(F("  frame_err="));  Serial.print(frame_errors);
    if (rx_bytes == 0) {
      Serial.println(F("  NO BYTES on pin 0 -- check Pi TX (pin 8) -> Teensy pin 0, and GND-GND"));
    } else if (rx_packets == 0) {
      Serial.println(F("  bytes but no valid packets -- baud mismatch? set RAW_HEX_DUMP 1 to see them"));
    } else {
      Serial.print(F("  last packet "));  Serial.print(millis() - last_rx_ms);
      Serial.println(F(" ms ago"));
    }
  }
}
