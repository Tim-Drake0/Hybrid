
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
};
TSY_Payload tsy_pkt;

// Layer 2 - DAQ Nano adds its own fields, embeds TSY_Payload
struct __attribute__((packed)) DAQ_Payload  {
    uint32_t    daq_nano_timestamp;
    int8_t      daq_nanoRSSI;
    TSY_Payload tsy;
};
DAQ_Payload daq_pkt;

// Layer 3 - Ctrl Nano adds its own fields, embeds DAQ_Payload
struct __attribute__((packed)) CTRL_Payload {
    uint32_t    ctrl_nano_timestamp;
    int8_t      ctrl_nanoRSSI;
    DAQ_Payload daq;         // daq data appended
};
CTRL_Payload ctrl_pkt;



struct NANO_Payload // Payload to teensy
{
  uint32_t timestamp = 0; 
  uint8_t valve_cmds = 0;
  uint8_t pyro_cmds = 0;
  uint8_t arm_cmd = 0;
  int RSSI = 0;
};
NANO_Payload nano_pkt;


static uint8_t crc8(const uint8_t *data, uint8_t len) {
    uint8_t crc = 0x00;
    while (len--) crc ^= *data++;
    return crc;
}

void send_response(uint8_t start0, uint8_t start1, uint8_t resp_id, const void *payload, uint8_t payload_len) {
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

    rf95.send(buf, i);
    rf95.waitPacketSent();
    digitalWrite(RADIO_LED, LOW);
    last_time_rx = millis(); // save new time of most recent transmission

    *len_ptr   = i;
    *ready_ptr = 1;
}

void handle_telemetry() {
    daq_pkt.daq_nano_timestamp = millis(),
    daq_pkt.daq_nanoRSSI = rf95.lastRssi();
    daq_pkt.tsy = tsy_pkt;  
    send_response(TELEM_FRAME_START_0, TELEM_FRAME_START_1, 0x69, &daq_pkt, sizeof(daq_pkt));
}

// reading serial from teensy
int readSync(HardwareSerial &ser) {
    unsigned long starttime = millis();

    // wait for first byte with timeout
    unsigned long t = millis();
    while (ser.available() < 1) {
        if (millis() - t > 1000) return 0;
    }
    byte b0 = ser.read();

    while (true) {
        // wait for next byte with timeout
        t = millis();
        while (ser.available() < 1) {
            if (millis() - t > 1000) return 0;
        }
        byte b1 = ser.read();

        if (b0 == TELEM_FRAME_START_0 && b1 == TELEM_FRAME_START_1) return 1;

        b0 = b1;  // slide the window

        // 1 sec timeout
        if(millis()-starttime > 1000){
            return 0;
        }
    }
}

bool readPacket() {
    if (readSync(Serial) != 1) return false;

    unsigned long t;

    t = millis();
    while (Serial.available() < 2) { if (millis()-t > 500) return false; }
    byte resp_id = Serial.read();
    byte length  = Serial.read();

    byte payload[256];
    if (length > 0) {
        t = millis();
        while (Serial.available() < length) { if (millis()-t > 500) return false; }
        Serial.readBytes(payload, length);
    }

    if (length == sizeof(TSY_Payload)) {
    memcpy(&tsy_pkt, payload, sizeof(TSY_Payload));
    }

    t = millis();
    while (Serial.available() < 2) { if (millis()-t > 500) return false; }
    byte crc_b = Serial.read();
    byte end_b = Serial.read();

    return true;
}
