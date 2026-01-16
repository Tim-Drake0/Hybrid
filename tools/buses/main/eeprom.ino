
char eepromFilename[10];

void readEEPROM(){
    strcpy(eepromFilename, "eeprom.txt");
    File eepromFile = SD.open(eepromFilename);  
    // read eeprom values
    char line[64];
    int idx = 0;
    while (eepromFile.available()) {
        char c = eepromFile.read();
        if (c == '\r') continue;   // ignore C  
        if (c == '\n') {
            line[idx] = 0;         // terminate string
            parseLine(line);
            idx = 0;
        } else if (idx < sizeof(line) - 1) {
            line[idx++] = c;
        }
    }
    // Handle last line if no newline
    if (idx > 0) {
        line[idx] = 0;
        parseLine(line);
    }
    eepromFile.close();

    MySerial.print("testMode: "); MySerial.println(eeprom.testMode);
    MySerial.print("recordData: "); MySerial.println(eeprom.recordData);
    MySerial.print("serialOut: "); MySerial.println(eeprom.serialOut);
    
}

void parseLine(char *line) {
    char key[32];
    int value;

    // Split "testMode 1"
    if (sscanf(line, "%31s %d", key, &value) != 2)
        return;   // bad line

    bool v = (value != 0);

    if (!strcmp(key, "testMode")) {
        eeprom.testMode = v;
    }
    else if (!strcmp(key, "recordData")) {
        eeprom.recordData = v;
    }
    else if (!strcmp(key, "serialOut")) {
        eeprom.serialOut = v;
    }
}
