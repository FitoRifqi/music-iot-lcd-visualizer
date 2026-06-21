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

byte vBar1[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F};
byte vBar2[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F};
byte vBar3[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F};
byte vBar4[8] = {0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F};
byte vBar5[8] = {0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte vBar6[8] = {0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte vBar7[8] = {0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte vBar8[8] = {0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  lcd.init();
  lcd.backlight();
  loadMusicChars();
  lcd.clear();
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

  analogWrite(LED_PIN, map(ram, 0, 100, 0, 255));
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

  int pipeIndex = data.indexOf('|');
  if (pipeIndex == -1) {
    return;
  }

  String lcdData = data.substring(0, pipeIndex);
  int brightness = constrain(data.substring(pipeIndex + 1).toInt(), 0, 255);

  byte column = 0;
  int startIndex = 0;

  while (column < LCD_COLUMNS && startIndex <= lcdData.length()) {
    int commaIndex = lcdData.indexOf(',', startIndex);
    String valueText = commaIndex == -1
      ? lcdData.substring(startIndex)
      : lcdData.substring(startIndex, commaIndex);

    int value = constrain(valueText.toInt(), 0, 8);
    lcd.setCursor(column, 1);
    value > 0 ? lcd.write(value) : lcd.print(" ");

    if (commaIndex == -1) {
      break;
    }

    startIndex = commaIndex + 1;
    column++;
  }

  analogWrite(LED_PIN, brightness);
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

  String displayText = "Now Playing: " + songTitle + "   ";
  if (scrollPos >= displayText.length()) {
    scrollPos = 0;
  }

  String currentView = displayText.substring(scrollPos, scrollPos + LCD_COLUMNS);
  while (currentView.length() < LCD_COLUMNS) {
    currentView += " ";
  }

  lcd.setCursor(0, 0);
  lcd.print(currentView);
  scrollPos++;
  lastScrollTime = millis();
}

void readSerialInput() {
  while (Serial.available() > 0) {
    char receivedChar = Serial.read();

    if (receivedChar == '\n') {
      parseAndRender(inputBuffer);
      inputBuffer = "";
      return;
    }

    inputBuffer += receivedChar;
  }
}

void loop() {
  scrollTrackTitle();
  readSerialInput();
}
