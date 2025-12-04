#include "src/busPwr.h"
#include <Arduino.h>
#include <HardwareSerial.h>

HardwareSerial MySerial(USART1);

uint8_t packet[12];  // 3x10 bits -> 30 bits -> 4 bytes
unsigned long lastSendTime = 0;

// Read analog voltage and apply calibration
uint16_t readVoltage(int pin) {
    uint16_t raw = analogRead(pin);
    return raw;
}

void setup() {
    MySerial.begin(115200);
    memset(packet, 0, busPwr.size);
}

void loop() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastSendTime >= 1000 / busPwr.frequency) {
        lastSendTime = currentMillis;

        uint16_t batt = analogRead(busPwr.battVolts.pin); 
        uint16_t volt3V = analogRead(busPwr.voltage3V.pin); 
        uint16_t volt5V = analogRead(busPwr.voltage5V.pin); 

        // header is ABBA
        packet[0] = 0xAB;
        packet[1] = 0xBA;

        // time in milliseconds
        packet[2] = (currentMillis >> 24) & 0xFF; // Most significant byte (MSB)
        packet[3] = (currentMillis >> 16) & 0xFF;
        packet[4] = (currentMillis >> 8)  & 0xFF;
        packet[5] = currentMillis & 0xFF;         // Least significant byte (LSB)

        // battery voltage
        packet[6] = (batt >> 8) & 0xFF;  // High byte (bits 9–8)
        packet[7] = batt & 0xFF;         // Low byte (bits 7–0)

        packet[8] = (volt3V >> 8) & 0xFF;  // High byte (bits 9–8)
        packet[9] = volt3V & 0xFF;         // Low byte (bits 7–0)

        packet[10] = (volt5V >> 8) & 0xFF;  // High byte (bits 9–8)
        packet[11] = volt5V & 0xFF;         // Low byte (bits 7–0)
        
        // Send packet
        MySerial.write(packet, busPwr.size);
    }
}
