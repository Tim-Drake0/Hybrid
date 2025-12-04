#ifndef BUSPWR_H
#define BUSPWR_H

#include <Arduino.h>

struct FieldConfig {
    int initVal;
    const char* unit;
    int startByte;
    int bytes;
    int bits;
    double c0;
    double c1;
    uint32_t pin;
};

struct BusPwrConfig {
    int id;
    int size;
    int frequency; // Hz
    const char* endian;
    FieldConfig battVolts;
    FieldConfig voltage3V;
    FieldConfig voltage5V;


    const FieldConfig* getField(const char* fieldName) const;
    int bufferSize() const;
    void serialize(uint16_t* values, uint8_t* buffer) const;
};

extern const BusPwrConfig busPwr;

#endif