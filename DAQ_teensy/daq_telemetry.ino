
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

// State machine info
typedef enum { WAIT_START0, WAIT_START1, READ_ID, READ_LEN, READ_PAYLOAD, READ_CRC, READ_END0, READ_END1 } ParseState;

static ParseState   parse_state  = WAIT_START0;
static uint8_t      parse_buf[258];
static uint16_t     parse_idx    = 0;
static uint8_t      parse_len    = 0;
static uint8_t      parse_id     = 0;


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
    digitalWrite(RADIO_LED, HIGH);

    *len_ptr   = i;
    *ready_ptr = 1;
}

void handleTelemetry(){
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
    uint8_t calc;  // ← declare here to avoid scope issues in switch
    while (Serial.available()) {
        uint8_t b = Serial.read();
        switch (parse_state) {
            case WAIT_START0:
                if (b == TELEM_FRAME_START_0) parse_state = WAIT_START1;
                break;
            case WAIT_START1:
                parse_state = (b == TELEM_FRAME_START_1) ? READ_ID : WAIT_START0;
                break;
            case READ_ID:
                parse_id = b;
                parse_buf[0] = b;
                parse_state = READ_LEN;
                break;
            case READ_LEN:
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
                calc = crc8(parse_buf, 2 + parse_len);
                if (calc == b) {
                    parse_state = READ_END0;   // wait for 0xEF first
                } else {
                    parse_state = WAIT_START0;
                }
                break;
            case READ_END0:
                parse_state = (b == FRAME_END_0) ? READ_END1 : WAIT_START0;
                break;
            case READ_END1:
                parse_state = WAIT_START0;
                if (b == FRAME_END_1 && parse_len == sizeof(DAQ_Payload)) {
                    memcpy(&daq_pkt, &parse_buf[2], sizeof(DAQ_Payload));
                    return true;
                }
                break;
        }
    }
    return false;
}

void readRadioPacket(uint8_t *buf, uint8_t len){
// Minimum frame size: START0 START1 ID LEN [PAYLOAD] CRC END0 END1
    uint8_t min_frame = 2 + 1 + 1 + sizeof(Switch_Payload) + 1 + 2;
    if (len < min_frame) return; // too short

    uint8_t *p = buf;

    // Check start bytes
    if (p[0] != TELEM_FRAME_START_0 || p[1] != TELEM_FRAME_START_1) return;

    uint8_t id      = p[2];
    uint8_t pay_len = p[3];

    // Validate length matches expected struct
    if (pay_len != sizeof(Switch_Payload)) return;

    // CRC check over [ID, LEN, PAYLOAD]
    uint8_t calc = crc8(&p[2], 2 + pay_len);
    uint8_t recv_crc = p[2 + 2 + pay_len]; // byte right after payload
    if (calc != recv_crc) return;

    // Check end bytes
    if (p[2 + 2 + pay_len + 1] != FRAME_END_0) return;
    if (p[2 + 2 + pay_len + 2] != FRAME_END_1) return;

    // All good — decom into struct
    memcpy(&sw_pkt, &p[4], sizeof(Switch_Payload));

    last_time_rx = millis(); // reset abort timer on good packet
}
/*
    if (readSync(Serial) != 1) return false;

    unsigned long t;

    t = millis();
    while (Serial.available() < 2) { if (millis()-t > 100) return false; }
    byte resp_id = Serial.read();
    byte length  = Serial.read();

    uint8_t payload[258];  // 1 (resp_id) + 1 (length) + 256 (max payload)
    uint16_t payload_len = 0;

    payload[payload_len++] = resp_id;
    payload[payload_len++] = length;

    if (length > 0) {
        t = millis();
        while (Serial.available() < length) { if (millis()-t > 100) return false; }
        Serial.readBytes(&payload[payload_len], length);
        payload_len += length;
    }

    t = millis();
    while (Serial.available() < 2) { if (millis()-t > 100) return false; }
    byte crc_b = Serial.read();
    byte end_b = Serial.read();

    uint8_t calculated = crc8(payload, payload_len);

    if(calculated == crc_b){
        if (length == sizeof(DAQ_Payload)) {
        memcpy(&daq_pkt, &payload[2], sizeof(DAQ_Payload));
        }


        return true;
    }
    return false;
    */
