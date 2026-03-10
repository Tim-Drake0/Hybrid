
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


static uint8_t crc8(const uint8_t *data, uint8_t len) {
    uint8_t crc = 0x00;
    while (len--) crc ^= *data++;
    return crc;
}

void sendPacket(uint8_t start0, uint8_t start1, uint8_t resp_id, const void *payload, uint8_t payload_len) {
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

void handle_serial() {
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t len = sizeof(buf);
    
    if (rf95.waitAvailableTimeout(200)) {
        // Should be a reply message for us now   
        rf95.recv(buf, &len);

        ctrl_pkt.ctrl_nano_timestamp = millis(),
        ctrl_pkt.ctrl_nanoRSSI = rf95.lastRssi();
        // buf layout: 2 start + 1 resp_id + 1 length = 4 bytes header, then payload starts
        memcpy(&ctrl_pkt.daq, &buf[4], sizeof(DAQ_Payload));
        
        sendPacket(TELEM_FRAME_START_0, TELEM_FRAME_START_1, 0x69, &ctrl_pkt, sizeof(ctrl_pkt));


    } else {
        CON_ERR = 1;
    }

}

bool handle_telemetry(const void *payload, uint8_t payload_len){
    uint8_t *buf;
    uint8_t *len_ptr;
    volatile uint8_t *ready_ptr;
    
    buf       = telem_buf;
    len_ptr   = &telem_len;
    ready_ptr = &telem_ready;

    uint8_t i = 0;
    
    buf[i++] = TELEM_FRAME_START_0;
    buf[i++] = TELEM_FRAME_START_1;
    buf[i++] = 0x69;
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

    return 0;
}