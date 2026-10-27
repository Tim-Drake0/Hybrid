// switch_packet_test.ino -- Teensy 4.1 bench test for the ground station's
// switch-state packet (serial_writer.CMD_SWITCH_STATES).
//
// Listens on Serial1 (the Pi's radio UART) and prints the switch states to
// the USB serial monitor: the full state whenever it changes, plus a link
// status line every 2 s.
//
// Wiring (both sides are 3.3 V logic -- no level shifting needed):
//   Pi GPIO14 / UART0 TX (header pin 8)  ->  Teensy pin 0 (RX1)
//   Pi GND (e.g. header pin 6)           ->  Teensy GND
// Teensy RX only listens, so it can sit on the line alongside the radio.
//
// Packet (all multi-byte values little-endian):
//   DE AD | ID=0x10 | LEN=3 | seq (u8) | switch bits (u16) | CRC | EF BE
//   CRC = XOR of ID, LEN and the payload bytes.

#define RADIO_SERIAL      Serial1    // RX1 = pin 0, TX1 = pin 1
#define RADIO_BAUD        115200     // gui_settings.RADIO_BAUD_RATE
#define RAW_HEX_DUMP      0          // 1 = also print every received byte in hex (debug)
#define ACTIVITY_LED      13         // on-board LED blinks while bytes arrive

#define CMD_FRAME_START_0 0xDE
#define CMD_FRAME_START_1 0xAD
#define FRAME_END_0       0xEF
#define FRAME_END_1       0xBE
#define CMD_SWITCH_STATES 0x10
#define SWITCH_PAYLOAD_LEN 3
#define MAX_PAYLOAD_LEN   128

// Bit N of the switch field. Keep in sync with
// serial_writer.SWITCH_PACKET_BITS in the ground station code.
static const char *SWITCH_NAMES[] = {
  "FILL",        // bit 0
  "VENT",        // bit 1
  "MOV",         // bit 2
  "SPARE_VLV",   // bit 3
  "ARM",         // bit 4
  "PYRO_FIRE",   // bit 5
  "PYRO_CH",     // bit 6  (1 = channel 1, 0 = channel 2)
  "AUTO_FIRE",   // bit 7
  "TM_EN",       // bit 8
  "REC_EN",      // bit 9
  "CAMERA_EN",   // bit 10
  "SPARE1",      // bit 11
  "SPARE2",      // bit 12
};
static const uint8_t NUM_SWITCHES = sizeof(SWITCH_NAMES) / sizeof(SWITCH_NAMES[0]);

// == Frame parser =============================================================
typedef enum { WAIT_START0, WAIT_START1, READ_ID, READ_LEN, READ_PAYLOAD, READ_CRC, READ_END0, READ_END1 } ParseState;

static ParseState parse_state = WAIT_START0;
static uint8_t    parse_buf[2 + MAX_PAYLOAD_LEN];   // ID, LEN, payload
static uint8_t    parse_idx = 0;
static uint8_t    parse_len = 0;

// Link statistics
static uint32_t rx_bytes    = 0;      // every byte seen on RX1, valid or not
static uint32_t rx_packets  = 0;
static uint32_t crc_errors  = 0;
static uint32_t frame_errors = 0;
static uint32_t missed_seq  = 0;
static uint32_t last_rx_ms  = 0;

static int16_t  last_seq    = -1;
static int32_t  last_bits   = -1;     // -1 = nothing received yet

static uint8_t crc8(const uint8_t *data, uint8_t len) {
  uint8_t crc = 0x00;
  while (len--) crc ^= *data++;
  return crc;
}

static void printSwitches(uint16_t bits, uint8_t seq) {
  Serial.print(F("[seq "));
  Serial.print(seq);
  Serial.print(F("] bits=0x"));
  if (bits < 0x1000) Serial.print('0');
  if (bits < 0x100)  Serial.print('0');
  if (bits < 0x10)   Serial.print('0');
  Serial.println(bits, HEX);

  for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
    Serial.print(F("  "));
    Serial.print(SWITCH_NAMES[i]);
    for (uint8_t pad = strlen(SWITCH_NAMES[i]); pad < 10; pad++) Serial.print(' ');
    Serial.println(bitRead(bits, i) ? F("ON") : F("off"));
  }
}

static void handlePacket(uint8_t id, const uint8_t *payload, uint8_t len) {
  if (id != CMD_SWITCH_STATES) return;           // some other command -- ignore
  if (len != SWITCH_PAYLOAD_LEN) { frame_errors++; return; }

  uint8_t  seq  = payload[0];
  uint16_t bits = (uint16_t)payload[1] | ((uint16_t)payload[2] << 8);

  rx_packets++;
  last_rx_ms = millis();
  if (last_seq >= 0) missed_seq += (uint8_t)(seq - last_seq - 1);
  last_seq = seq;

  if ((int32_t)bits != last_bits) {             // only print on change
    printSwitches(bits, seq);
    last_bits = bits;
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
// (Tools > USB Type must include "Serial"). Serial1 is only ever read.
void setup() {
  Serial.begin(115200);                // USB -- baud is ignored, always full USB speed
  RADIO_SERIAL.begin(RADIO_BAUD);
  pinMode(ACTIVITY_LED, OUTPUT);
  while (!Serial && millis() < 3000) {}

  Serial.print(F("Switch packet test -- listening on Serial1 RX (pin 0) @ "));
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
    Serial.print(F("-- bytes="));     Serial.print(rx_bytes);
    Serial.print(F("  packets="));    Serial.print(rx_packets);
    Serial.print(F("  missed="));     Serial.print(missed_seq);
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
