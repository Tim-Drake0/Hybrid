









void beginSD(void){
    // SD card set up
    if (!SD.begin(BUILTIN_SDCARD)) { // If SD start unsuccessful
    Serial.println("SD Card initalize.. Failed");
    } else { // If SD start successful
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
    }  
}

