/*
  KRISHI-DRISHTI :: OLED Deep Diagnostic
  Scans I2C, tries all OLED init modes, draws test patterns.
  Upload this FIRST to confirm wiring, then re-flash Controller firmware.
*/
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== KRISHI-DRISHTI OLED DIAGNOSTIC ===");

  // Try both I2C pin pairs
  int sdaPins[] = {21, 21, 4, 4};
  int sclPins[] = {22, 22, 15, 15};
  int addresses[] = {0x3C, 0x3D, 0x3C, 0x3D};

  Serial.println("\n--- Step 1: I2C Bus Scan (SDA=21, SCL=22) ---");
  Wire.begin(21, 22);
  Wire.setClock(100000);
  bool found = false;
  for (int addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    byte err = Wire.endTransmission();
    if (err == 0) {
      Serial.printf("  [FOUND] Device at I2C address 0x%02X\n", addr);
      found = true;
    }
  }
  if (!found) Serial.println("  [NONE] No I2C devices found on SDA=21 SCL=22!");

  // Try 0x3C
  Serial.println("\n--- Step 2: SSD1306 begin() at 0x3C ---");
  bool ok3C = display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  Serial.printf("  begin(0x3C) = %s\n", ok3C ? "OK" : "FAIL");

  if (ok3C) {
    Serial.println("  Drawing white fill...");
    display.clearDisplay();
    display.fillRect(0, 0, 128, 64, SSD1306_WHITE);
    display.display();
    delay(1000);

    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(10, 10);
    display.print("HELLO!");
    display.setTextSize(1);
    display.setCursor(5, 40);
    display.print("SSD1306 OK: 0x3C");
    display.display();
    Serial.println("  White fill + HELLO text drawn. Check OLED!");
  } else {
    Serial.println("  Trying 0x3D...");
    bool ok3D = display.begin(SSD1306_SWITCHCAPVCC, 0x3D);
    Serial.printf("  begin(0x3D) = %s\n", ok3D ? "OK" : "FAIL");
    if (ok3D) {
      display.clearDisplay();
      display.fillRect(0, 0, 128, 64, SSD1306_WHITE);
      display.display();
      delay(500);
      display.clearDisplay();
      display.setTextColor(SSD1306_WHITE);
      display.setTextSize(1);
      display.setCursor(5, 25);
      display.print("OK at 0x3D - Fix addr!");
      display.display();
    } else {
      Serial.println("  BOTH addresses FAILED.");
      Serial.println("  CHECK: SDA->GPIO21, SCL->GPIO22, VCC->3.3V, GND->GND");
    }
  }

  // Print contrast info
  Serial.println("\n--- Step 3: Contrast registers ---");
  display.ssd1306_command(0x81); // SSD1306_SETCONTRAST
  display.ssd1306_command(0xFF); // MAX contrast
  display.dim(false);
  Serial.println("  Contrast set to 0xFF (maximum)");
  Serial.println("  dim(false) called");

  Serial.println("\n=== DIAGNOSTIC COMPLETE ===");
  Serial.println("If OLED is still black after white-fill, check:");
  Serial.println("  1. VCC connected to 3.3V (NOT 5V)");
  Serial.println("  2. GND connected to GND");
  Serial.println("  3. SDA -> GPIO 21 on ESP32");
  Serial.println("  4. SCL -> GPIO 22 on ESP32");
  Serial.println("  5. Display contrast pot (some modules have trim pot)");
  Serial.println("  6. Try disconnecting & reconnecting power");
}

void loop() {
  // Blink test pattern every 2 seconds
  static unsigned long lastBlink = 0;
  static bool invert = false;
  if (millis() - lastBlink > 2000) {
    lastBlink = millis();
    invert = !invert;
    display.invertDisplay(invert);
    Serial.printf("  [BLINK] invertDisplay(%d) - If still black: hardware fault\n", invert);
  }
}
