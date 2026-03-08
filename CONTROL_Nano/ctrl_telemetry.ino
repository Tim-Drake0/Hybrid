
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

unsigned long last_time_serial = 0;
int dt_serial = 100;

typedef struct __attribute__((packed)) {
    uint32_t time = 0; 
    uint8_t states = 0;
    float loadCell = 0;
    float PT_tank = 0;
    float battVolts = 0;
    int RSSI = 0;
} TelemetryDataFrame;

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

    Serial.write(buf, i);
    last_time_serial = millis(); // save new time of most recent transmission

    *len_ptr   = i;
    *ready_ptr = 1;
}

void handle_telemetry() {
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t len = sizeof(buf);
    
    if (rf95.waitAvailableTimeout(500)) {
        // Should be a reply message for us now   
        rf95.recv(buf, &len);

        TelemetryDataFrame pkt;

        uint8_t state;
        state |= (buf[0] & 1) << 0;  // C1 into bit 0
        state |= (buf[1] & 1) << 1;  // C2 into bit 1

        pkt.time      = millis();
        pkt.states    = state;
        pkt.loadCell  = word(buf[3], buf[2])*0.939416365405;
        pkt.PT_tank   = (word(buf[5],buf[4])*3.255177532)+(-123.3104072);
        pkt.battVolts = word(buf[7], buf[6])*0.0213;
        pkt.RSSI      = abs(rf95.lastRssi());
        
        send_response(TELEM_FRAME_START_0, TELEM_FRAME_START_1, 0x69, &pkt, sizeof(pkt));


    } else {
        CON_ERR = 1;
    }

}