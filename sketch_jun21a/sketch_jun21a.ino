#include <LiquidCrystal_I2C.h>
#include <Wire.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

const byte LED_PIN = 9;
const byte LCD_COLUMNS = 16;
const unsigned long SCROLL_DELAY_MS = 250;

String inputBuffer = "";
String songTitle = "";
String currentMode = "MONITOR";

int scrollPos = 0;
unsigned long lastScrollTime = 0;

// Smooth LED fade — independent dari frame rate Python
float     ledSmooth           = 0.0f;
byte      ledTarget           = 0;
unsigned long lastLedTick     = 0;
const float   LED_DECAY       = 0.88f;  // decay per 16ms tick (~600ms ke nol)
const unsigned long LED_TICK  = 16;     // ~62fps update rate

byte vBar1[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F};
byte vBar2[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F};
byte vBar3[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F};
byte vBar4[8] = {0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F};
byte vBar5[8] = {0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte vBar6[8] = {0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte vBar7[8] = {0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte vBar8[8] = {0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};

// Instant attack, smooth exponential decay
void setLedTarget(byte value) {
  ledTarget = value;
  if ((float)value > ledSmooth) {
    ledSmooth = (float)value;  // langsung naik saat beat
  }
}

void updateLedSmooth() {
  if (millis() - lastLedTick < LED_TICK) return;
  lastLedTick = millis();
  if ((float)ledTarget > ledSmooth) {
    ledSmooth = (float)ledTarget;
  } else if (ledSmooth > 0.5f) {
    ledSmooth *= LED_DECAY;
    if (ledSmooth < 0.5f) ledSmooth = 0.0f;
  }
  analogWrite(LED_PIN, (byte)ledSmooth);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  lcd.init();
  lcd.backlight();
  loadMusicChars();
  lcd.clear();

  // Tampilkan splash singkat — sekaligus flush buffer serial yang kotor
  lcd.setCursor(0, 0);
  lcd.print("  Music IoT LCD ");
  lcd.setCursor(0, 1);
  lcd.print("   Loading...   ");
  delay(1500);
  lcd.clear();

  // Buang sisa data serial yang mungkin masuk saat reset
  while (Serial.available()) Serial.read();
}

void loadMusicChars() {
  lcd.createChar(1, vBar1);
  lcd.createChar(2, vBar2);
  lcd.createChar(3, vBar3);
  lcd.createChar(4, vBar4);
  lcd.createChar(5, vBar5);
  lcd.createChar(6, vBar6);
  lcd.createChar(7, vBar7);
  lcd.createChar(8, vBar8);
}

void switchMode(String nextMode) {
  if (currentMode == nextMode) {
    return;
  }

  currentMode = nextMode;
  lcd.clear();

  if (nextMode == "MUSIC") {
    loadMusicChars();
  }
}

void printPadded(String text, byte width) {
  lcd.print(text);
  for (byte i = text.length(); i < width; i++) {
    lcd.print(" ");
  }
}

void renderSystemData(String data) {
  switchMode("MONITOR");

  int firstComma = data.indexOf(',');
  int secondComma = data.indexOf(',', firstComma + 1);
  int thirdComma = data.indexOf(',', secondComma + 1);

  if (firstComma == -1 || secondComma == -1 || thirdComma == -1) {
    return;
  }

  String timeText = data.substring(4, firstComma);
  String dateText = data.substring(firstComma + 1, secondComma);
  int cpu = constrain(data.substring(secondComma + 1, thirdComma).toInt(), 0, 100);
  int ram = constrain(data.substring(thirdComma + 1).toInt(), 0, 100);

  lcd.setCursor(0, 0);
  printPadded(timeText + " | CPU:" + (cpu < 10 ? " " : "") + String(cpu) + "%", LCD_COLUMNS);

  lcd.setCursor(0, 1);
  printPadded(dateText + " | RAM:" + (ram < 10 ? " " : "") + String(ram) + "%", LCD_COLUMNS);

  setLedTarget((byte)map(ram, 0, 100, 0, 255));
}

void renderTrackTitle(String data) {
  switchMode("MUSIC");
  songTitle = data.substring(4);
  scrollPos = 0;
}

void renderVisualizer(String data) {
  if (currentMode != "MUSIC") {
    return;
  }

  // Format paket: "col0,col1,...|brightness|bpm"
  int pipeIdx1 = data.indexOf('|');
  if (pipeIdx1 == -1) return;

  String lcdData = data.substring(0, pipeIdx1);
  String rest    = data.substring(pipeIdx1 + 1);

  int pipeIdx2 = rest.indexOf('|');
  int brightness, bpm;
  if (pipeIdx2 == -1) {
    brightness = constrain(rest.toInt(), 0, 255);
    bpm = 0;
  } else {
    brightness = constrain(rest.substring(0, pipeIdx2).toInt(), 0, 255);
    bpm        = constrain(rest.substring(pipeIdx2 + 1).toInt(), 0, 999);
  }

  // Render 12 bar visualizer di kolom 0-11 (ROW 1)
  const byte VIZ_COLS = 12;
  byte column = 0;
  int startIndex = 0;

  while (column < VIZ_COLS && startIndex <= (int)lcdData.length()) {
    int commaIndex = lcdData.indexOf(',', startIndex);
    String valueText = commaIndex == -1
      ? lcdData.substring(startIndex)
      : lcdData.substring(startIndex, commaIndex);

    int value = constrain(valueText.toInt(), 0, 8);
    lcd.setCursor(column, 1);  // row 1 = baris bawah
    if (value > 0) lcd.write((uint8_t)value);
    else lcd.print(" ");

    if (commaIndex == -1) break;
    startIndex = commaIndex + 1;
    column++;
  }

  // Isi sisa kolom visualizer yang belum terisi
  while (column < VIZ_COLS) {
    lcd.setCursor(column, 1);
    lcd.print(" ");
    column++;
  }

  // Tampilkan BPM di kolom 12-15 (ROW 1), right-aligned 4 karakter
  String bpmText;
  if (bpm > 0) {
    bpmText = String(bpm);
    while ((int)bpmText.length() < 4) bpmText = " " + bpmText;
    if ((int)bpmText.length() > 4) bpmText = bpmText.substring(0, 4);
  } else {
    bpmText = "    ";  // kosong saat BPM belum terdeteksi
  }
  lcd.setCursor(12, 1);
  lcd.print(bpmText);

  setLedTarget((byte)brightness);
}

void parseAndRender(String data) {
  data.trim();

  if (data.startsWith("TXT:")) {
    renderTrackTitle(data);
    return;
  }

  if (data.startsWith("SYS:")) {
    renderSystemData(data);
    return;
  }

  renderVisualizer(data);
}

void scrollTrackTitle() {
  if (currentMode != "MUSIC" || songTitle.length() == 0) {
    return;
  }

  if (millis() - lastScrollTime <= SCROLL_DELAY_MS) {
    return;
  }

  // Tambah padding di depan agar judul tidak langsung muncul dari tepi
  String displayText = songTitle + "   ";
  if (scrollPos >= (int)displayText.length()) {
    scrollPos = 0;
  }

  // Ambil 16 karakter dari posisi scroll saat ini
  String currentView = "";
  for (byte i = 0; i < LCD_COLUMNS; i++) {
    int idx = (scrollPos + i) % displayText.length();
    currentView += displayText[idx];
  }

  // Tulis hanya ke ROW 0 — row 1 khusus visualizer
  lcd.setCursor(0, 0);
  lcd.print(currentView);
  scrollPos++;
  lastScrollTime = millis();
}

void readSerialInput() {
  while (Serial.available() > 0) {
    char receivedChar = Serial.read();

    if (receivedChar == '\n') {
      if (inputBuffer.length() > 0) {
        parseAndRender(inputBuffer);
      }
      inputBuffer = "";
      return;
    }

    // Proteksi buffer overflow (Arduino RAM terbatas)
    if (inputBuffer.length() < 200) {
      inputBuffer += receivedChar;
    }
  }
}

void loop() {
  scrollTrackTitle();
  readSerialInput();
  updateLedSmooth();  // smooth PWM fade independen
}
