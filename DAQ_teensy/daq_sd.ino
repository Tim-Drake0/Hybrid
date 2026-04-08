



char flightDir[16];





void beginSD(void){
    // SD card set up
    if (!SD.begin(BUILTIN_SDCARD)) { // If SD start unsuccessful
        Serial.println("SD Card initalize.. Failed");
        return;
    }

    // If SD start successful
    Serial.println("SD card init OK!");
    bitWrite(daq_pkt.sensor_states, 0, 1);

    int i = 0;
    filename = "data"+String(i)+".csv"; // Generate a unique filename
    while (SD.exists(filename.c_str())) { // Check if the filename already exists
        i += 1; // increase filename number
        filename = "data"+String(i)+".csv"; // Generate a new filename
    }
    Serial.println("Logging data to " + filename);
    datafile = SD.open(filename.c_str(),FILE_WRITE); // Open data file
    if (datafile) { // If datafile open
        datafile.println(fileheader); // Write file header
        datafile.close();
    }

    load_config();
}

int findNextFlightDir(void)
{
    for (int i = 1; i <= 999; i++) {
        snprintf(flightDir, sizeof(flightDir), "FLT%03d", i);
        if (!SD.exists(flightDir)) {
            return 1;  /* directory doesn't exist yet, use this one */
        }
    }
    return 0;  /* all 999 slots taken */
}

void load_config() {

    File f = SD.open("config.txt", FILE_READ);
    if (!f) {
        Serial.println("ERROR: No config.txt found, using defaults");
        return;
    }

    char line[64];
    while (f.available()) {
        // Read a line manually
        int len = 0;
        while (f.available() && len < (int)sizeof(line) - 1) {
            char c = f.read();
            if (c == '\n') break;
            line[len++] = c;
        }
        line[len] = '\0';

        // Skip comments and blank lines
        if (len == 0 || line[0] == '#' || line[0] == '\r' || line[0] == '\n') continue;

        char key[32], value[32];
        if (sscanf(line, " %31[^=]= %31s", key, value) != 2) continue;

        // Trim trailing spaces from key
        int klen = strlen(key);
        while (klen > 0 && key[klen-1] == ' ') key[--klen] = '\0';

        if      (strcmp(key, "PT1_Cal0")       == 0) eeprom.pt1_c0        = atof(value);
        else if (strcmp(key, "PT1_Cal1")       == 0) eeprom.pt1_c1        = atof(value);
        else if (strcmp(key, "PT2_Cal0")       == 0) eeprom.pt2_c0        = atof(value);
        else if (strcmp(key, "PT2_Cal1")       == 0) eeprom.pt2_c1        = atof(value);
        else if (strcmp(key, "PT3_Cal0")       == 0) eeprom.pt3_c0        = atof(value);
        else if (strcmp(key, "PT3_Cal1")       == 0) eeprom.pt3_c1        = atof(value);
        else if (strcmp(key, "PT4_Cal0")       == 0) eeprom.pt4_c0        = atof(value);
        else if (strcmp(key, "PT4_Cal1")       == 0) eeprom.pt4_c1        = atof(value);
        else if (strcmp(key, "Servo1_open")    == 0) eeprom.servo1_open   = atof(value);
        else if (strcmp(key, "Servo1_close")   == 0) eeprom.servo1_close  = atof(value);
        else if (strcmp(key, "Servo2_open")    == 0) eeprom.servo2_open   = atof(value);
        else if (strcmp(key, "Servo2_close")   == 0) eeprom.servo2_close  = atof(value);
        else if (strcmp(key, "Servo3_open")    == 0) eeprom.servo3_open   = atof(value);
        else if (strcmp(key, "Servo3_close")   == 0) eeprom.servo3_close  = atof(value);
        else if (strcmp(key, "Servo4_open")    == 0) eeprom.servo4_open   = atof(value);
        else if (strcmp(key, "Servo4_close")   == 0) eeprom.servo4_close  = atof(value);
        else if (strcmp(key, "SD Sample Rate") == 0) eeprom.SD_sample_rate = atoi(value);
    }

    f.close();
    
    Serial.println("=== Config Loaded ===");
    Serial.print("PT1_Cal0: ");       Serial.println(eeprom.pt1_c0, 6);
    Serial.print("PT1_Cal1: ");       Serial.println(eeprom.pt1_c1, 6);
    Serial.print("PT2_Cal0: ");       Serial.println(eeprom.pt2_c0, 6);
    Serial.print("PT2_Cal1: ");       Serial.println(eeprom.pt2_c1, 6);
    Serial.print("PT3_Cal0: ");       Serial.println(eeprom.pt3_c0, 6);
    Serial.print("PT3_Cal1: ");       Serial.println(eeprom.pt3_c1, 6);
    Serial.print("PT4_Cal0: ");       Serial.println(eeprom.pt4_c0, 6);
    Serial.print("PT4_Cal1: ");       Serial.println(eeprom.pt4_c1, 6);
    Serial.print("Servo1_open: ");    Serial.println(eeprom.servo1_open,  2);
    Serial.print("Servo1_close: ");   Serial.println(eeprom.servo1_close, 2);
    Serial.print("Servo2_open: ");    Serial.println(eeprom.servo2_open,  2);
    Serial.print("Servo2_close: ");   Serial.println(eeprom.servo2_close, 2);
    Serial.print("Servo3_open: ");    Serial.println(eeprom.servo3_open,  2);
    Serial.print("Servo3_close: ");   Serial.println(eeprom.servo3_close, 2);
    Serial.print("Servo4_open: ");    Serial.println(eeprom.servo4_open,  2);
    Serial.print("Servo4_close: ");   Serial.println(eeprom.servo4_close, 2);
    Serial.print("SD_sample_rate: "); Serial.println(eeprom.SD_sample_rate);
    Serial.println("=====================");
}

