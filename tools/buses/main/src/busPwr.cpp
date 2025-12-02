#include "busPwr.h"
#include <string.h>
#include <Arduino.h>

const BusPwrConfig busPwr = {
    100,
    12,
    50,
    "little",
    { 65535, "V", 0, 2, 10, -4.368197737, 0.01759218372, A3},
    { 65535, "V", 2, 2, 10, 0.00,         1.00         , A1},
    { 65535, "V", 4, 2, 10, 0.00,         1.00         , A2}
};

const FieldConfig* BusPwrConfig::getField(const char* fieldName) const {
    if (strcmp(fieldName, "battVolts") == 0) return &battVolts;
    if (strcmp(fieldName, "voltage3V") == 0) return &voltage3V;
    if (strcmp(fieldName, "voltage5V") == 0) return &voltage5V;
    return nullptr;
}

//int BusPwrConfig::bufferSize() const {
//    int size = 0;
//    size = 2+4+battVolts.bytes; // + voltage3V.bytes + voltage5V.bytes;
//    return size;
//}

void BusPwrConfig::serialize(uint16_t* values, uint8_t* buffer) const {
    memset(buffer, 0, busPwr.size);
    

}
