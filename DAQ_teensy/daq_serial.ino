// daq_serial.ino — Serial command interface
// 
// Servo Cal Workflow:
//   "scal"        → print all servo cals, enter servo-select mode
//   "s1"–"s4"     → select a servo, enter adjust mode
//   "o+x" / "o-x" → nudge OPEN position by x degrees
//   "c+x" / "c-x" → nudge CLOSE position by x degrees
//   "test"        → momentarily move selected servo to open then back to close (visual check)
//   "save"        → write current eeprom values back to config.txt on SD
//   "back"        → return to servo select
//   "exit"        → leave cal mode
//
// Other commands (always available):
//   "debug"       → toggle print_debug
//   "reload"      → re-read config.txt from SD

// --- State machine ---
enum SerialMode {
  MODE_IDLE,
  MODE_SERVO_SELECT,   // waiting for "s1"–"s4"
  MODE_SERVO_ADJUST    // waiting for "o+x", "o-x", "c+x", "c-x", "test", "save", "exit"
};

static SerialMode serialMode = MODE_IDLE;
static int        calServo   = 0;    // 1-4, which servo is selected

// --- Helpers ---

static void printServoCals() {
  Serial.println(F("--- Servo Calibration ---"));
  Serial.print(F("S1 (PHIL)  open="));  Serial.print(eeprom.servo1_open);
  Serial.print(F("  close="));          Serial.println(eeprom.servo1_close);
  Serial.print(F("S2 (VENT)  open="));  Serial.print(eeprom.servo2_open);
  Serial.print(F("  close="));          Serial.println(eeprom.servo2_close);
  Serial.print(F("S3 (MOV)   open="));  Serial.print(eeprom.servo3_open);
  Serial.print(F("  close="));          Serial.println(eeprom.servo3_close);
  Serial.print(F("S4 (SPARE) open="));  Serial.print(eeprom.servo4_open);
  Serial.print(F("  close="));          Serial.println(eeprom.servo4_close);
  Serial.println(F("-------------------------"));
}

// Return a reference to the correct eeprom float for the currently selected servo/side
static float getCalValue(int servo, bool openSide) {
  if (servo == 1) return openSide ? eeprom.servo1_open : eeprom.servo1_close;
  if (servo == 2) return openSide ? eeprom.servo2_open : eeprom.servo2_close;
  if (servo == 3) return openSide ? eeprom.servo3_open : eeprom.servo3_close;
  if (servo == 4) return openSide ? eeprom.servo4_open : eeprom.servo4_close;
  return 0;
}

static void setCalValue(int servo, bool openSide, float val) {
  // Clamp to valid servo range
  val = constrain(val, 0, 180);
  if (servo == 1) { if (openSide) eeprom.servo1_open  = val; else eeprom.servo1_close = val; }
  if (servo == 2) { if (openSide) eeprom.servo2_open  = val; else eeprom.servo2_close = val; }
  if (servo == 3) { if (openSide) eeprom.servo3_open  = val; else eeprom.servo3_close = val; }
  if (servo == 4) { if (openSide) eeprom.servo4_open  = val; else eeprom.servo4_close = val; }
}

static void printAdjustPrompt() {
  Serial.print(F("S")); Serial.print(calServo);
  Serial.print(F("  open="));  Serial.print(getCalValue(calServo, true),  1);
  Serial.print(F("  close=")); Serial.println(getCalValue(calServo, false), 1);
  Serial.println(F("  o+x / o-x  nudge open  |  c+x / c-x  nudge close  |  test  |  save  |  back  |  exit"));
}

// Physically move a servo to a given position using live eeprom values
static void applyServoPos(int servo, bool openSide) {
  float pos = getCalValue(servo, openSide);
  if (servo == 1) servo1.write(pos);
  if (servo == 2) servo2.write(pos);
  if (servo == 3) servo3.write(pos);
  if (servo == 4) servo4.write(pos);
}

// Quick test: move to open, wait 1 s, move to close
static void testServo(int servo) {
  Serial.print(F("Testing S")); Serial.print(servo);
  Serial.println(F("  → open"));
  applyServoPos(servo, true);
  delay(1000);
  Serial.println(F("  → close"));
  applyServoPos(servo, false);
  delay(500);
  Serial.println(F("  done."));
}

// --- Main parse function, call from loop() ---
void handleSerial() {
  if (!Serial.available()) return;

  // Read a full line (terminated by '\n')
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd.length() == 0) return;

  // Echo back so user can see what was received
  Serial.print(F("> ")); Serial.println(cmd);

  // --- Commands available in any mode ---
  if (cmd.equalsIgnoreCase("debug")) {
    eeprom.print_debug = !eeprom.print_debug;
    Serial.print(F("print_debug = ")); Serial.println(eeprom.print_debug);
    return;
  }
  if (cmd.equalsIgnoreCase("reload")) {
    load_config();
    return;
  }

  // --- IDLE mode ---
  if (serialMode == MODE_IDLE) {
    if (cmd.equalsIgnoreCase("scal")) {
      printServoCals();
      Serial.println(F("Select servo: s1  s2  s3  s4"));
      serialMode = MODE_SERVO_SELECT;
    } else {
      Serial.println(F("Commands: scal | debug | reload"));
    }
    return;
  }

  // --- SERVO SELECT mode ---
  if (serialMode == MODE_SERVO_SELECT) {
    if (cmd.equalsIgnoreCase("exit")) {
      Serial.println(F("Exiting cal mode."));
      serialMode = MODE_IDLE;
      return;
    }
    if (cmd.length() == 2 && (cmd[0]=='s'||cmd[0]=='S') && cmd[1]>='1' && cmd[1]<='4') {
      calServo = cmd[1] - '0';
      serialMode = MODE_SERVO_ADJUST;
      Serial.print(F("Selected S")); Serial.println(calServo);
      printAdjustPrompt();
    } else {
      Serial.println(F("Type s1, s2, s3, or s4  (or 'exit')"));
    }
    return;
  }

  // --- SERVO ADJUST mode ---
  if (serialMode == MODE_SERVO_ADJUST) {

    if (cmd.equalsIgnoreCase("exit")) {
      Serial.println(F("Exiting cal mode."));
      serialMode = MODE_IDLE;
      return;
    }

    if (cmd.equalsIgnoreCase("test")) {
      testServo(calServo);
      printAdjustPrompt();
      return;
    }

    if (cmd.equalsIgnoreCase("save")) {
      if (save_config()) {
        Serial.println(F("Config saved to SD card."));
      } else {
        Serial.println(F("ERROR: Save failed (SD card error)."));
      }
      printAdjustPrompt();
      return;
    }

    // Back to servo select
    if (cmd.equalsIgnoreCase("back")) {
      serialMode = MODE_SERVO_SELECT;
      printServoCals();
      Serial.println(F("Select servo: s1  s2  s3  s4"));
      return;
    }

    // o+x / o-x  or  c+x / c-x
    if (cmd.length() >= 3 && (cmd[0]=='o' || cmd[0]=='O' || cmd[0]=='c' || cmd[0]=='C')
                           && (cmd[1]=='+' || cmd[1]=='-')) {
      bool isOpen = (cmd[0]=='o' || cmd[0]=='O');
      float delta = cmd.substring(2).toFloat();
      if (cmd[1] == '-') delta = -delta;
      float newVal = getCalValue(calServo, isOpen) + delta;
      setCalValue(calServo, isOpen, newVal);
      applyServoPos(calServo, isOpen);
      printAdjustPrompt();
      return;
    }

    Serial.println(F("o+x / o-x  |  c+x / c-x  |  test  |  save  |  back  |  exit"));
    return;
  }
}
